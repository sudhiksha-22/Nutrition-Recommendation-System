# -*- coding: utf-8 -*-
"""Final_recommender.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1gQJDuWa8Pn8BX1yN0zYWFvYi0DxRqAIm

Final collaborative Recommender
"""

import pandas as pd
import numpy as np
import sklearn
from sklearn.neighbors import NearestNeighbors
from collections import Counter
from sklearn.metrics import precision_score, recall_score, f1_score
import warnings
warnings.filterwarnings('ignore')
from supabase import create_client, Client
import pandas as pd

url = "https://nkculiajetxhofngayca.supabase.co"  
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5rY3VsaWFqZXR4aG9mbmdheWNhIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczMDkwMjQ1OSwiZXhwIjoyMDQ2NDc4NDU5fQ.itjwX6V6OUTMjwmbOa5JVCHzYUX02ogAKsoTK7q5aSg"  
supabase: Client = create_client(url, key)

class Recommender:

    def __init__(self,profiles,recent_activity,dataset):
        self.df = dataset
        self.profiles = profiles
        self.recent_activity = recent_activity

    def get_features(self,dataframe):
        #getting dummies of dataset
        nutrient_dummies = dataframe.Nutrient.str.get_dummies()
        disease_dummies = dataframe.Disease.str.get_dummies(sep=' ')
        diet_dummies = dataframe.Diet.str.get_dummies(sep=' ')
        feature_df = pd.concat([nutrient_dummies,disease_dummies,diet_dummies],axis=1)

        return feature_df

    def find_neighbors(self,dataframe,features,k):
        features_df = self.get_features(dataframe)
        total_features = features_df.columns
        d = dict()
        for i in total_features:
            d[i]= 0
        for i in features:
            d[i] = 1
        final_input = list(d.values())

        similar_neighbors = self.k_neighbor([final_input],features_df,dataframe,k)
        return similar_neighbors

    def k_neighbor(self,inputs,feature_df,dataframe,k):

        #initializing model with k neighbors
        model = NearestNeighbors(n_neighbors=k,algorithm='ball_tree')

        # fitting model with dataset features
        model.fit(feature_df)

        df_results = pd.DataFrame(columns=list(dataframe.columns))
        # getting distance and indices for k nearest neighbor
        distnaces , indices = model.kneighbors(inputs)

        for i in list(indices):
            df_results = pd.concat([df_results,dataframe.loc[i]], ignore_index=True)

        df_results = df_results.reset_index(drop=True)
        return df_results

    def user_based(self,features,user_id):

        similar_users = self.find_neighbors(self.profiles,features,10)
        users = list(similar_users.User_Id)

        results = self.recent_activity[self.recent_activity.User_Id.isin(users)] #taking acitivies

        results = results[results['User_Id']!=user_id] # selecting those which are not reviewed by user

        meals = list(results.Meal_Id.unique())

        results = self.df[self.df.Meal_Id.isin(meals)]

        results = results.filter(['Meal_Id','Name','Nutrient','Veg_Non','Review'])

        results = results.drop_duplicates(subset=['Name'])
        results = results.reset_index(drop=True)
        return results

    def recent_activity_based(self,user_id):
        recent_df = self.recent_activity[self.recent_activity['User_Id']==user_id]
        meal_ids = list(recent_df.Meal_Id.unique())
        recent_data = self.df[self.df.Meal_Id.isin(meal_ids)][['Nutrient','catagory','Disease','Diet']].reset_index(drop=True)

        disease = []
        diet = []
        for i in range(recent_data.shape[0]):
            for j in recent_data.loc[i,'Disease'].split():
                disease.append(j)
        for i in range(recent_data.shape[0]):
            for j in recent_data.loc[i,'Diet'].split():
                diet.append(j)

        value_counts = recent_data.Nutrient.value_counts()
        m = recent_data.Nutrient.value_counts().mean()
        features = list(value_counts[recent_data.Nutrient.value_counts()>m].index)
        a = dict(Counter(disease))

        m = np.mean(list(a.values()))
        for i in a.items():
            if i[1]>m:
                features.append(i[0])
        a = dict(Counter(diet))
        m = np.mean(list(a.values()))
        for i in a.items():
            if i[1]>m:
                features.append(i[0])

        similar_neighbors = self.find_neighbors(self.df,features,20)
        return similar_neighbors.filter(['Meal_Id','Name','Nutrient','Veg_Non','Review'])

    def recommend(self, user_id):
    # Get user's profile features by ID
        profile = self.profiles[self.profiles['User_Id'] == user_id]
        features = []
        features.append(profile['Nutrient'].values[0])
        features.extend(profile['Disease'].values[0].split())
        features.extend(profile['Diet'].values[0].split())

        # Generate recommendations based on user-based and recent activity-based methods
        df1 = self.user_based(features, user_id)
        df2 = self.recent_activity_based(user_id)
        df = pd.concat([df1, df2])

        # Ensure 'Meal_Type' column is included in the results
        if 'Meal_type' not in df.columns:
            df['Meal_type'] = self.df['Meal_type']
        print(df.columns)
        print(df['Meal_type'].unique())

        # Create a dictionary to store categorized meals
        grouped_recommendations = {
            'breakfast': [],
            'lunch': [],
            'dinner': []
        }

        # Loop through the dataframe and assign meals to their respective categories
        for _, row in df.iterrows():
            meal_types = row['Meal_type'].split()  # Assuming Meal_Type can have multiple values
            for meal_type in meal_types:
                if meal_type in grouped_recommendations:
                    grouped_recommendations[meal_type].append(row.to_dict())


        return grouped_recommendations


  # user id of current user

# Fetch user profiles
profiles_data = supabase.table("user_profile").select("*").execute()
profiles = pd.DataFrame(profiles_data.data)


# Fetch recent activity
recent_activity_data = supabase.table("recent_Activity").select("*").execute()
recent_activity = pd.DataFrame(recent_activity_data.data)

# Fetch main dataset
dataset_data = supabase.table("dataset").select("*").execute()
dataset = pd.DataFrame(dataset_data.data)




